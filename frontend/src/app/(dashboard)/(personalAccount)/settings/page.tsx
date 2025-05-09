'use client';

import { Separator } from '@/components/ui/separator';
import { createClient } from '@/lib/supabase/client';
import { useState, useEffect } from 'react';
import Image from 'next/image';
export default function PersonalAccountSettingsPage() {
  const [user, setUser] = useState<{
    name: string;
    email: string;
    avatar: string;
  }>({
    name: 'Loading...',
    email: 'loading@example.com',
    avatar: '',
  });

  
  // Fetch user data
  useEffect(() => {
    const fetchUserData = async () => {
      const supabase = createClient();
      const { data } = await supabase.auth.getUser();

      if (data.user) {
        setUser({
          name:
            data.user.user_metadata?.name ||
            data.user.email?.split('@')[0] ||
            'User',
          email: data.user.email || '',
          avatar: data.user.user_metadata?.avatar_url || '',
        });
      }
    };

    fetchUserData();
  }, []);


  return (
    <div>
      <h1>Settings</h1>
      <Separator />
      <div className="flex items-center space-x-4 py-4">
        <div className="relative w-20 h-20 rounded-full overflow-hidden border-2 border-accent">
          <Image 
            src={user.avatar || '/default-avatar.png'} 
            alt="Avatar" 
            width={80} 
            height={80}
            className="object-cover"
          />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-semibold text-foreground">{user.name}</h2>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">Add integrations by clicking the integrations button on the left</p>
    </div>
  );
}
