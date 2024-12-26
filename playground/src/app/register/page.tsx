'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useDispatch } from 'react-redux'
import { login } from '@/store/reducers/authReducer'
import { authService } from '@/services/authService'

export default function Page() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const router = useRouter()
  const dispatch = useDispatch()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const result = await authService.register(username, password)
    if (result.success) {
      dispatch(login(username))
      router.push('/chatbot')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <input 
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
      />
      <input 
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button type="submit">Register</button>
    </form>
  )
}