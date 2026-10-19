import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium transition-colors duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 cursor-pointer md:min-h-9",
  {
    variants: {
      variant: {
        primary: "bg-accent-solid text-on-accent hover:opacity-90",
        secondary: "border border-border bg-surface text-text hover:bg-subtle",
        ghost: "text-text hover:bg-subtle",
        danger: "bg-deny text-white hover:opacity-90",
        success: "bg-allow text-white hover:opacity-90",
      },
      size: { md: "", sm: "min-h-11 px-3 text-[13px] md:min-h-8", icon: "size-11 p-0 md:size-9" },
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
