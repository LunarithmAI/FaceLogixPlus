import api from './api';
import type {
  User,
  CreateUserRequest,
  UpdateUserRequest,
  UserListParams,
  UserListResponse,
  EnrollFaceRequest,
  EnrollFaceResponse,
  BulkImportResponse,
} from '@/types/user';

const USERS_BASE = '/users';

export const usersApi = {
  /**
   * Get list of unique departments in the organization
   */
  async getDepartments(): Promise<string[]> {
    const response = await api.get<string[]>(`${USERS_BASE}/departments`);
    return response.data;
  },
  /**
   * Get paginated list of users
   */
  async list(params: UserListParams = {}): Promise<UserListResponse> {
    const response = await api.get<UserListResponse>(USERS_BASE, { params });
    return response.data;
  },

  /**
   * Get a single user by ID
   */
  async get(userId: string): Promise<User> {
    const response = await api.get<User>(`${USERS_BASE}/${userId}`);
    return response.data;
  },

  /**
   * Create a new user
   */
  async create(data: CreateUserRequest): Promise<User> {
    const response = await api.post<User>(USERS_BASE, data);
    return response.data;
  },

  /**
   * Update an existing user
   */
  async update(userId: string, data: UpdateUserRequest): Promise<User> {
    const response = await api.patch<User>(`${USERS_BASE}/${userId}`, data);
    return response.data;
  },

  /**
   * Delete a user
   */
  async delete(userId: string): Promise<void> {
    await api.delete(`${USERS_BASE}/${userId}`);
  },

  /**
   * Reset user password (admin only)
   */
  async resetPassword(userId: string, newPassword: string): Promise<void> {
    await api.post(`${USERS_BASE}/${userId}/reset-password`, {
      new_password: newPassword,
    });
  },

  /**
   * Activate a user
   */
  async activate(userId: string): Promise<User> {
    const response = await api.post<User>(`${USERS_BASE}/${userId}/activate`);
    return response.data;
  },

  /**
   * Deactivate a user
   */
  async deactivate(userId: string): Promise<User> {
    const response = await api.post<User>(`${USERS_BASE}/${userId}/deactivate`);
    return response.data;
  },

  /**
   * Enroll face embeddings for a user
   */
  async enrollFace(data: EnrollFaceRequest): Promise<EnrollFaceResponse> {
    const response = await api.post<EnrollFaceResponse>(
      `${USERS_BASE}/${data.user_id}/enroll-face`,
      { images: data.images }
    );
    return response.data;
  },

  /**
   * Delete face embeddings for a user
   */
  async deleteFaceEmbeddings(userId: string): Promise<void> {
    await api.delete(`${USERS_BASE}/${userId}/face-embeddings`);
  },

  /**
   * Get user's face enrollment status
   */
  async getFaceStatus(userId: string): Promise<{ has_face: boolean; embeddings_count: number }> {
    const response = await api.get<{ has_face: boolean; embeddings_count: number }>(
      `${USERS_BASE}/${userId}/face-status`
    );
    return response.data;
  },

  async downloadBulkTemplate(): Promise<void> {
    const response = await api.get(`${USERS_BASE}/bulk-import/template`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'bulk_import_template.csv');
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  async bulkImport(file: File, skipExisting: boolean = true): Promise<BulkImportResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<BulkImportResponse>(
      `${USERS_BASE}/bulk-import?skip_existing=${skipExisting}`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      }
    );
    return response.data;
  },
};

export default usersApi;
