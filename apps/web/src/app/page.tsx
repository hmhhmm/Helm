import { EmptyState, ScreenHeader } from "@/components/screen";
import { en } from "@/i18n/en";

export default function TodayPage() {
  return (
    <>
      <ScreenHeader title={en.today.title} answer="Am I okay, and what needs me?" />
      <EmptyState message={en.today.empty} />
    </>
  );
}
