export const authService = {
    login: async (username: string, password: string) => {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      return { success: true, user: username }
    },
    
    register: async (username: string, password: string) => {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      return { success: true, user: username }
    }
  }