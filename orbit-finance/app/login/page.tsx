// Signing in is core's, and the session cookie is the one every Orbit app
// reads, so signing in here signs you in to all of them. The page still says
// which app this is, because that is the one thing the address bar hides.
export { LoginPage as default, metadata } from "@/src/platform/app/login-page";
