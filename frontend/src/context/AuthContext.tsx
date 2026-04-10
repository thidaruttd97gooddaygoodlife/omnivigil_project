'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Role, mockUsers, hasPageAccess, getDefaultPage } from '@/lib/mockData';
import { authApi } from '@/lib/api';

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    login: (username: string, password: string) => Promise<{ success: boolean; error?: string; role?: Role }>;
    loginAsRole: (role: Role) => void;
    logout: () => void;
    hasAccess: (page: string) => boolean;
    isDemoMode: boolean;
    setDemoMode: (mode: boolean) => void;
    allUsers: User[];
    fetchUsers: () => Promise<void>;
    addUser: (user: Omit<User, 'id' | 'createdAt'>) => void;
    editUser: (id: string, updates: Partial<User>) => void;
    deleteUser: (id: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isDemoMode, setIsDemoMode] = useState(false);
    const [allUsers, setAllUsers] = useState<User[]>(mockUsers);

    // Initial check for existing token
    useEffect(() => {
        const token = localStorage.getItem('omnivigil_token');
        if (token) {
            authApi.get('/auth/me')
                .then(res => {
                    const apiUser = res.data;
                    setUser({
                        id: apiUser.id || 'u' + Date.now(),
                        username: apiUser.username,
                        password: '***',
                        name: apiUser.full_name || apiUser.username,
                        role: apiUser.role as Role,
                        email: apiUser.email || `${apiUser.username}@omnivigil.io`,
                        createdAt: apiUser.created_at || new Date().toISOString()
                    });
                })
                .catch(() => {
                    // Token invalid/expired
                    localStorage.removeItem('omnivigil_token');
                })
                .finally(() => {
                    setIsLoading(false);
                });
        } else {
            setIsLoading(false);
        }

        const savedMode = localStorage.getItem('omnivigil_demo_mode');
        if (savedMode === 'true') {
            setIsDemoMode(true);
            const savedUsers = localStorage.getItem('omnivigil_demo_users');
            if (savedUsers) {
                try {
                    setAllUsers(JSON.parse(savedUsers));
                } catch {
                    localStorage.removeItem('omnivigil_demo_users');
                }
            } else {
                setAllUsers(mockUsers);
            }
        } else {
            setIsDemoMode(false);
            if (token) {
                fetchUsers();
            } else {
                setAllUsers([]);
            }
        }
    }, []);

    const setDemoMode = useCallback((mode: boolean) => {
        setIsDemoMode(mode);
        localStorage.setItem('omnivigil_demo_mode', mode.toString());
        if (mode) {
             const savedUsers = localStorage.getItem('omnivigil_demo_users');
             setAllUsers(savedUsers ? JSON.parse(savedUsers) : mockUsers);
        } else {
             setAllUsers([]);
             const token = localStorage.getItem('omnivigil_token');
             if (token) fetchUsers();
        }
    }, []);

    const fetchUsers = useCallback(async () => {
        try {
            const res = await authApi.get('/users');
            const apiUsers = res.data.map((u: any) => ({
                id: u.id.toString(),
                username: u.username,
                password: '***',
                name: u.full_name || u.username,
                email: u.email || `${u.username}@omnivigil.io`,
                role: u.role as Role,
                createdAt: u.created_at
            }));
            setAllUsers(apiUsers);
        } catch (err) {
            console.error("Failed to fetch LIVE API users", err);
        }
    }, []);

    const login = useCallback(async (username: string, password: string) => {
        try {
            const payload = { username, password };
            
            // The ms1-auth expects a JSON body (LoginRequest BaseModel) instead of Form Data
            const res = await authApi.post<{ access_token: string }>('/auth/login', payload);
            
            // Login via Form is always Live Mode
            setDemoMode(false);

            const token = res.data.access_token;
            localStorage.setItem('omnivigil_token', token);
            
            // Fetch users after login automatically
            fetchUsers();
            
            // Fetch me to get role, name, and email
            const meRes = await authApi.get('/auth/me');
            const apiUser = meRes.data;
            
            setUser({
                id: apiUser.id || 'u' + Date.now(),
                username: apiUser.username,
                password: '***',
                name: apiUser.full_name || apiUser.username,
                role: apiUser.role as Role,
                email: apiUser.email || `${apiUser.username}@omnivigil.io`,
                createdAt: apiUser.created_at || new Date().toISOString()
            });
            return { success: true, role: apiUser.role as Role };
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            const errorMsg = Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : (detail || 'Invalid username or password');
            return { success: false, error: errorMsg };
        }
    }, []);

    const loginAsRole = useCallback((role: Role) => {
        const found = mockUsers.find(u => u.role === role);
        if (found) {
            setUser(found);
            setDemoMode(true);
            // Fallback for mock login
            localStorage.setItem('omnivigil_user', JSON.stringify(found));
        }
    }, [setDemoMode]);

    const logout = useCallback(() => {
        setUser(null);
        setAllUsers([]);
        localStorage.removeItem('omnivigil_token');
        localStorage.removeItem('omnivigil_user');
        localStorage.removeItem('omnivigil_demo_mode');
    }, []);

    const hasAccess = useCallback((page: string) => {
        if (!user) return false;
        return hasPageAccess(user.role, page);
    }, [user]);

    const addUser = useCallback(async (newUser: Omit<User, 'id' | 'createdAt'>) => {
        if (isDemoMode) {
            const u: User = {
                ...newUser,
                id: 'u' + Date.now(),
                createdAt: new Date().toISOString(),
            };
            setAllUsers(prev => {
                const updated = [...prev, u];
                localStorage.setItem('omnivigil_demo_users', JSON.stringify(updated));
                return updated;
            });
            return;
        }
        
        // Live API Logic
        try {
            const payload = { 
                username: newUser.username, 
                password: newUser.password, 
                role: newUser.role,
                full_name: newUser.name,
                email: newUser.email
            };
            await authApi.post('/users', payload);
            await fetchUsers();
            alert("✅ User created successfully!");
        } catch (err: any) {
            console.error("Failed to create LIVE API user", err.response?.data);
            alert("❌ Error creating user: " + (err.response?.data?.detail || err.message));
        }
    }, [isDemoMode, fetchUsers]);

    const deleteUser = useCallback(async (id: string) => {
        if (isDemoMode) {
            setAllUsers(prev => {
                const updated = prev.filter(u => u.id !== id);
                localStorage.setItem('omnivigil_demo_users', JSON.stringify(updated));
                return updated;
            });
            return;
        }

        // Live API Logic
        try {
            const targetUsername = allUsers.find(u => u.id === id)?.username;
            if(!targetUsername) {
                alert("❌ Could not find username for ID: " + id);
                return;
            }
            console.log("Deleting user:", targetUsername);
            await authApi.delete(`/users/${targetUsername}`);
            await fetchUsers();
            alert(`✅ User "${targetUsername}" deleted!`);
        } catch (err: any) {
            console.error("Failed to delete LIVE API user", err.response?.data);
            alert("❌ Error deleting user: " + (err.response?.data?.detail || err.message));
        }
    }, [isDemoMode, allUsers, fetchUsers]);

    const editUser = useCallback(async (id: string, updates: Partial<User>) => {
        if (isDemoMode) {
             setAllUsers(prev => {
                const updated = prev.map(u => u.id === id ? { ...u, ...updates } : u);
                localStorage.setItem('omnivigil_demo_users', JSON.stringify(updated));
                return updated;
            });
            return;
        }

        // Live API Logic
        try {
            const targetUsername = allUsers.find(u => u.id === id)?.username;
            if(!targetUsername) return;
            
            const payload: any = {};
            if(updates.role) payload.role = updates.role;
            if(updates.password && updates.password !== '***') payload.password = updates.password;
            if(updates.name) payload.full_name = updates.name;
            if(updates.email) payload.email = updates.email;

            await authApi.put(`/users/${targetUsername}`, payload);
            await fetchUsers();
            alert("✅ User updated successfully!");
        } catch (err: any) {
             console.error("Failed to edit LIVE API user", err.response?.data);
             alert("❌ Error updating user: " + (err.response?.data?.detail || err.message));
        }
    }, [isDemoMode, allUsers, fetchUsers]);

    return (
        <AuthContext.Provider value={{
            user, isLoading, isDemoMode, setDemoMode, login, loginAsRole, logout, hasAccess, allUsers, fetchUsers, addUser, editUser, deleteUser
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}

export { getDefaultPage };
