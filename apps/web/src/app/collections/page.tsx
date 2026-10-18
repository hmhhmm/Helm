import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function CollectionsPage() {
  return (
    <>
      <ScreenHeader title={en.nav.collections} answer="Coming in a later phase." />
      <EmptyState message={en.today.empty} />
    </>
  );
}
