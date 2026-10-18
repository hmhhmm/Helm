import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function PaymentsPage() {
  return (
    <>
      <ScreenHeader title={en.nav.payments} answer="Coming in a later phase." />
      <EmptyState message={en.today.empty} />
    </>
  );
}
