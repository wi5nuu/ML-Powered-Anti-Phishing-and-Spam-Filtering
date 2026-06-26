import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Let React handle auth — no hard redirect on 401.
// The route guards and useMe() hook detect auth loss and redirect gracefully.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      console.warn('[auth] 401 detected — components should handle error or redirect')
    }
    return Promise.reject(err)
  }
)

export default api
