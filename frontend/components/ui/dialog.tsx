import * as React from "react"
import { cn } from "@/lib/utils"

const Dialog = ({ open, onOpenChange, children }: { open: boolean; onOpenChange: (open: boolean) => void; children: React.ReactNode }) => {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange(false)} />
      <div className="relative z-50 bg-background rounded-lg shadow-lg border max-w-md w-full max-h-[80vh] overflow-hidden">
        {children}
      </div>
    </div>
  )
}

const DialogHeader = ({ className, children }: { className?: string; children: React.ReactNode }) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left p-6", className)}>
    {children}
  </div>
)

const DialogTitle = ({ className, children }: { className?: string; children: React.ReactNode }) => (
  <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)}>
    {children}
  </h2>
)

const DialogContent = ({ className, children }: { className?: string; children: React.ReactNode }) => (
  <div className={cn("p-6 pt-0 overflow-y-auto max-h-[60vh]", className)}>
    {children}
  </div>
)

const DialogFooter = ({ className, children }: { className?: string; children: React.ReactNode }) => (
  <div className={cn("flex items-center p-6 pt-0", className)}>
    {children}
  </div>
)

export { Dialog, DialogHeader, DialogTitle, DialogContent, DialogFooter }
