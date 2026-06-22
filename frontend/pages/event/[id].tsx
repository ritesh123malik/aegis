import { useRouter } from "next/router";
import { useEffect } from "react";

export default function EventDetailPage() {
  const router = useRouter();
  const { id } = router.query;

  useEffect(() => {
    if (typeof id === "string") {
      router.replace(`/?event=${encodeURIComponent(id)}`);
    }
  }, [id, router]);

  return null;
}
