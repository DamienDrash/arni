"use client";

import { useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Typography from '@tiptap/extension-typography';
import { Bold, Italic, List, ListOrdered, Heading1, Heading2, Quote, Undo, Redo } from 'lucide-react';
import { T } from '@/lib/tokens';

const TiptapEditor = ({ content, onChange }: { content: string, onChange: (html: string) => void }) => {
    const editor = useEditor({
        extensions: [
            StarterKit,
            Typography,
        ],
        content: content, // Initialize with content
        editorProps: {
            attributes: {
                class: 'ariia-editor prose prose-sm sm:prose lg:prose-lg xl:prose-2xl max-w-none focus:outline-none min-h-[300px] p-4',
            },
        },
        onUpdate: ({ editor }) => {
            onChange(editor.getHTML());
        },
        immediatelyRender: false, // Fix SSR hydration mismatch
    });

    // Update editor content when prop changes (e.g. after fetch)
    useEffect(() => {
        if (editor && content && editor.getHTML() !== content) {
            // Only update if content is actually different to avoid cursor jumps/loops
            // For initial load, this works perfectly.
            editor.commands.setContent(content);
        }
    }, [content, editor]);

    if (!editor) {
        return null;
    }

    return (
        <div
            className="flex flex-col rounded-lg overflow-hidden h-full"
            style={{ border: `1px solid ${T.border}`, background: "#FAFBFF" }}
        >
            {/* Toolbar */}
            <div
                role="toolbar"
                aria-label="Text Editor Toolbar"
                className="flex items-center gap-1 p-2 overflow-x-auto"
                style={{ background: "#F1F4FF", borderBottom: `1px solid ${T.border}` }}
            >
                <button
                    type="button"
                    aria-label="Fett"
                    aria-pressed={editor.isActive('bold')}
                    onClick={() => editor.chain().focus().toggleBold().run()}
                    disabled={!editor.can().chain().focus().toggleBold().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('bold') ? "#11142D" : "#51556B", background: editor.isActive('bold') ? "#DDE4FF" : "transparent" }}
                    title="Bold"
                >
                    <Bold size={16} />
                </button>
                <button
                    type="button"
                    aria-label="Kursiv"
                    aria-pressed={editor.isActive('italic')}
                    onClick={() => editor.chain().focus().toggleItalic().run()}
                    disabled={!editor.can().chain().focus().toggleItalic().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('italic') ? "#11142D" : "#51556B", background: editor.isActive('italic') ? "#DDE4FF" : "transparent" }}
                    title="Italic"
                >
                    <Italic size={16} />
                </button>
                <div className="w-px h-6 mx-1" style={{ background: "#CCD3EE" }}></div>
                <button
                    type="button"
                    aria-label="Überschrift 1"
                    aria-pressed={editor.isActive('heading', { level: 1 })}
                    onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('heading', { level: 1 }) ? "#11142D" : "#51556B", background: editor.isActive('heading', { level: 1 }) ? "#DDE4FF" : "transparent" }}
                    title="Heading 1"
                >
                    <Heading1 size={16} />
                </button>
                <button
                    type="button"
                    aria-label="Überschrift 2"
                    aria-pressed={editor.isActive('heading', { level: 2 })}
                    onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('heading', { level: 2 }) ? "#11142D" : "#51556B", background: editor.isActive('heading', { level: 2 }) ? "#DDE4FF" : "transparent" }}
                    title="Heading 2"
                >
                    <Heading2 size={16} />
                </button>
                <div className="w-px h-6 mx-1" style={{ background: "#CCD3EE" }}></div>
                <button
                    type="button"
                    aria-label="Aufzählung"
                    aria-pressed={editor.isActive('bulletList')}
                    onClick={() => editor.chain().focus().toggleBulletList().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('bulletList') ? "#11142D" : "#51556B", background: editor.isActive('bulletList') ? "#DDE4FF" : "transparent" }}
                    title="Bullet List"
                >
                    <List size={16} />
                </button>
                <button
                    type="button"
                    aria-label="Nummerierte Liste"
                    aria-pressed={editor.isActive('orderedList')}
                    onClick={() => editor.chain().focus().toggleOrderedList().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('orderedList') ? "#11142D" : "#51556B", background: editor.isActive('orderedList') ? "#DDE4FF" : "transparent" }}
                    title="Ordered List"
                >
                    <ListOrdered size={16} />
                </button>
                <button
                    type="button"
                    aria-label="Zitat"
                    aria-pressed={editor.isActive('blockquote')}
                    onClick={() => editor.chain().focus().toggleBlockquote().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: editor.isActive('blockquote') ? "#11142D" : "#51556B", background: editor.isActive('blockquote') ? "#DDE4FF" : "transparent" }}
                    title="Quote"
                >
                    <Quote size={16} />
                </button>
                <div className="w-px h-6 mx-1" style={{ background: "#CCD3EE" }}></div>
                <button
                    type="button"
                    aria-label="Rückgängig"
                    onClick={() => editor.chain().focus().undo().run()}
                    disabled={!editor.can().chain().focus().undo().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: "#51556B" }}
                    title="Undo"
                >
                    <Undo size={16} />
                </button>
                <button
                    type="button"
                    aria-label="Wiederholen"
                    onClick={() => editor.chain().focus().redo().run()}
                    disabled={!editor.can().chain().focus().redo().run()}
                    className="btn btn-sm btn-ghost btn-square focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                    style={{ color: "#51556B" }}
                    title="Redo"
                >
                    <Redo size={16} />
                </button>
            </div>

            {/* Editor Content */}
            <div
                className="flex-1 overflow-y-auto cursor-text"
                style={{ background: "#FFFFFF" }}
                onClick={() => editor.chain().focus().run()}
            >
                <EditorContent editor={editor} className="h-full min-h-[300px]" aria-label="Rich Text Editor" />
            </div>
        </div>
    );
};

export default TiptapEditor;
