"use client";

import { useState, useCallback } from "react";
import { Dialog } from "./Dialog";

let confirmFn: ((result: boolean | string | null) => void) | null = null;
let promptFn: ((result: string | null) => void) | null = null;

export function useConfirm() {
    const [isOpen, setIsOpen] = useState(false);
    const [options, setOptions] = useState<{
        title: string;
        description?: string;
        confirmText?: string;
        cancelText?: string;
        isPrompt?: boolean;
        defaultValue?: string;
    }>({ title: "" });
    const [inputValue, setInputValue] = useState("");

    const confirm = useCallback(
        (title: string, description?: string, customConfirmText = "Confirm", customCancelText = "Cancel") => {
            return new Promise<boolean>((resolve) => {
                setOptions({
                    title,
                    description,
                    confirmText: customConfirmText,
                    cancelText: customCancelText,
                    isPrompt: false,
                });
                setIsOpen(true);
                confirmFn = resolve as (res: boolean | string | null) => void;
            });
        },
        []
    );

    const promptUser = useCallback(
        (title: string, defaultValue = "", description?: string, customConfirmText = "Submit", customCancelText = "Cancel") => {
            return new Promise<string | null>((resolve) => {
                setOptions({
                    title,
                    description,
                    confirmText: customConfirmText,
                    cancelText: customCancelText,
                    isPrompt: true,
                    defaultValue,
                });
                setInputValue(defaultValue);
                setIsOpen(true);
                promptFn = resolve as (res: string | null) => void;
            });
        },
        []
    );

    const handleClose = useCallback(() => {
        setIsOpen(false);
        if (options.isPrompt && promptFn) {
            promptFn(null);
            promptFn = null;
        } else if (confirmFn) {
            confirmFn(false);
            confirmFn = null;
        }
    }, [options.isPrompt]);

    const handleConfirm = useCallback(() => {
        setIsOpen(false);
        if (options.isPrompt && promptFn) {
            promptFn(inputValue);
            promptFn = null;
        } else if (confirmFn) {
            confirmFn(true);
            confirmFn = null;
        }
    }, [inputValue, options.isPrompt]);

    const ConfirmComponent = (
        <Dialog open={isOpen} onClose={handleClose} title={options.title} description={options.description}>
            {options.isPrompt ? (
                <div className="mt-4">
                    <input
                        type="text"
                        className="input input-bordered w-full"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        autoFocus
                        onKeyDown={(e) => {
                            if (e.key === "Enter") {
                                handleConfirm();
                            }
                        }}
                    />
                </div>
            ) : null}
            <div className="modal-action mt-6">
                <button className="btn btn-ghost" onClick={handleClose}>
                    {options.cancelText || "Cancel"}
                </button>
                <button className="btn btn-primary" onClick={handleConfirm}>
                    {options.confirmText || "Confirm"}
                </button>
            </div>
        </Dialog>
    );

    return { confirm, promptUser, ConfirmComponent };
}
