import { ReactNode, useEffect, useRef } from "react";

export interface DialogProps {
    open: boolean;
    onClose: () => void;
    title: string;
    description?: string;
    children: ReactNode;
}

export function Dialog({ open, onClose, title, description, children }: DialogProps) {
    const dialogRef = useRef<HTMLDialogElement>(null);

    useEffect(() => {
        const dialog = dialogRef.current;
        if (!dialog) return;

        if (open && !dialog.open) {
            dialog.showModal();
        } else if (!open && dialog.open) {
            dialog.close();
        }
    }, [open]);

    useEffect(() => {
        const handleCancel = (e: Event) => {
            e.preventDefault(); // Prevent default close to enforce controlled component behavior
            onClose();
        };

        const dialog = dialogRef.current;
        if (dialog) {
            dialog.addEventListener("cancel", handleCancel);
        }
        return () => {
            if (dialog) {
                dialog.removeEventListener("cancel", handleCancel);
            }
        };
    }, [onClose]);

    return (
        <dialog
            ref={dialogRef}
            className="modal"
            aria-labelledby="dialog-title"
            aria-describedby={description ? "dialog-description" : undefined}
        >
            <div className="modal-box">
                <h3 id="dialog-title" className="font-bold text-lg">{title}</h3>
                {description && <p id="dialog-description" className="py-2 text-sm opacity-70">{description}</p>}

                <div className="py-4">
                    {children}
                </div>
            </div>
            <form method="dialog" className="modal-backdrop">
                <button onClick={onClose}>close</button>
            </form>
        </dialog>
    );
}
