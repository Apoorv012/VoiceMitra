import { NextResponse, type NextRequest } from "next/server";

// A quick check before the signed-in screens load: no sign-in cookie at all -> straight to /login (and back
// after). It only looks for the cookie, it can't tell whether it is still valid -- the API checks that on
// every call, and the screens send the person to /login when it answers 401.
export function proxy(request: NextRequest) {
  if (request.cookies.has("vm_session")) return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  const login = new URL("/login", request.url);
  login.searchParams.set("next", pathname + search);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/patients/:path*", "/caregivers/:path*", "/operator/:path*", "/doctors/:path*", "/calls/:path*"],
};
