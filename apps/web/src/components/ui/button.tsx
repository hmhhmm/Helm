import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-contrast hover:opacity-90",
        secondary: "border border-border bg-surface text-text hover:bg-bg",
        ghost: "text-text hover:bg-bg",
        danger: "bg-deny text-white hover:opacity-90",
        success: "bg-allow text-white hover:opacity-90",
      },
      size: { md: "", sm: "min-h-11 px-3 text-xs md:min-h-9", icon: "size-11 p-0" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends React.ComponentProps<"button">, VariantProps<typeof button> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(button({ variant, size }), className)} {...props} />;
}
