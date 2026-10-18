import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function PolicyPage() {
  return (
    <>
      <ScreenHeader title={en.nav.policy} answer="Coming in a later phase." />
      <EmptyState message={en.today.empty} />
    </>
  );
}
