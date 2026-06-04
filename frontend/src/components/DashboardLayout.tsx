'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth();
    const router = useRouter();
    const [sidebarWidth, setSidebarWidth] = useState(260);

    useEffect(() => {
        if (!isLoading && !user) {
            router.replace('/login');
        }
    }, [user, isLoading, router]);

    useEffect(() => {
        const observer = new MutationObserver(() => {
            const sidebar = document.querySelector('aside');
            if (sidebar) {
                setSidebarWidth(sidebar.offsetWidth);
            }
        });
        const sidebar = document.querySelector('aside');
        if (sidebar) {
            setSidebarWidth(sidebar.offsetWidth);
            observer.observe(sidebar, { attributes: true, attributeFilter: ['style'] });
        }
        return () => observer.disconnect();
    }, [user]);

    if (isLoading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
                <div className="spinner" />
            </div>
        );
    }

    if (!user) return null;

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <Sidebar />
            <main style={{
                flex: 1,
                marginLeft: `${sidebarWidth}px`,
                padding: '28px 32px',
                transition: 'margin-left var(--transition-slow)',
                minHeight: '100vh',
                background: 'radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.03) 0%, transparent 60%)',
            }}>
                {children}
            </main>
        </div>
    );
}
