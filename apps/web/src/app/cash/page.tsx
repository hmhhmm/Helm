import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function CashPage() {
  return (
    <>
      <ScreenHeader title={en.nav.cash} answer="Coming in a later phase." />
      <EmptyState message={en.today.empty} />
    </>
  );
}
