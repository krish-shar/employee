import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Agent Conversation | Vale',
  description: 'Interactive agent conversation powered by Vale',
  openGraph: {
    title: 'Agent Conversation | Vale',
    description: 'Interactive agent conversation powered by Vale',
    type: 'website',
  },
};

export default function AgentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
