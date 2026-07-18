"""Shared form widget CSS classes (Tailwind)."""

FIELD = (
    "w-full rounded-md border border-stone-300 bg-white px-3.5 py-2.5 text-[15px] "
    "text-ink placeholder:text-stone-400 outline-none transition "
    "focus:border-vermilion focus:ring-2 focus:ring-vermilion/20"
)

FIELD_SM = FIELD

FILE = (
    "block w-full cursor-pointer rounded-xl border border-dashed border-line bg-paper "
    "px-3.5 py-3 text-sm text-ink file:mr-3 file:cursor-pointer file:rounded-full "
    "file:border-0 file:bg-ink file:px-4 file:py-2 file:text-xs file:font-bold file:text-white "
    "hover:border-vermilion/50"
)

CHECK = "h-4 w-4 rounded border-stone-300 text-vermilion focus:ring-vermilion/30"
