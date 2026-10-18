import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function AgentsPage() {
  return (
    <>
      <ScreenHeader title={en.nav.agents} answer="Coming in a later phase." />
      <EmptyState message={en.today.empty} />
    </>
  );
}
