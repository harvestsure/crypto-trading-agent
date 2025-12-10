import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Public routes that don't require authentication
  const publicRoutes = ["/login", "/register"]
  const isPublicRoute = publicRoutes.some((route) => pathname.startsWith(route))

  // Check if user has auth token
  const token = request.cookies.get("auth_token")?.value

  // Redirect to login if accessing protected route without token
  if (!isPublicRoute && !token) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("redirect", pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Redirect to home if accessing public route with token
  if (isPublicRoute && token) {
    return NextResponse.redirect(new URL("/", request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
}
