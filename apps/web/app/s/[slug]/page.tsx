import { ShareView } from "@/features/share/ShareView";

interface SharePageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function SharePage({ params }: SharePageProps) {
  const { slug } = await params;
  return <ShareView slug={slug} />;
}
