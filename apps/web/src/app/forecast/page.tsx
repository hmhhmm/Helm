import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function ForecastPage() {
  return (
    <>
      <ScreenHeader title={en.nav.forecast} answer="Coming in a later phase." />
      <EmptyState message={en.today.empty} />
    </>
  );
}
