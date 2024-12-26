import Link from "next/link"

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <h1>Welcome to Ten Agent</h1>
      <div>
        <Link href="/login">Login</Link>
        <Link href="/src/app/register">Register</Link>
      </div>
    </main>
  )
}