import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/queryClient'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { AdminRoute } from '@/components/AdminRoute'
import { Layout } from '@/components/Layout'
import { LoginPage } from '@/pages/LoginPage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { NewProjectPage } from '@/pages/NewProjectPage'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import { CatalogPage } from '@/pages/CatalogPage'
import { ProductsPage } from '@/pages/ProductsPage'
import { CatalogLoadsPage } from '@/pages/CatalogLoadsPage'
import { UsersAdminPage } from '@/pages/UsersAdminPage'
import { SetPasswordPage } from '@/pages/SetPasswordPage'

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/set-password" element={<SetPasswordPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<NewProjectPage />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="projects/new" element={<NewProjectPage />} />
              <Route path="projects/:id" element={<ProjectDetailPage />} />
              <Route element={<AdminRoute />}>
                <Route path="products" element={<ProductsPage />} />
                <Route path="catalog" element={<CatalogPage />} />
                <Route path="catalog/loads" element={<CatalogLoadsPage />} />
                <Route path="admin/users" element={<UsersAdminPage />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
