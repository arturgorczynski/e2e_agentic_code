"""Small, accessible HTML history list; native forms use the owned HTTP routes."""

import html


def history_html(service, token, selected, mode=None):
    rows = service.history(token, mode)
    active, deleted = [], []
    for row in rows:
        if mode is not None and row["mode"] != mode:
            continue
        identifier = html.escape(row["id"], quote=True)
        title = html.escape(row["title"], quote=True)
        base = f"/chats/{identifier}"
        if row["status"] != "active":
            deleted.append(
                f'<form action="{base}/restore" method="post" class="trash-row">'
                f'<span>{title}</span><button type="submit">Restore</button></form>'
            )
            continue
        current = ' aria-current="page"' if row["id"] == selected else ""
        active.append(
            f'<div class="history-row{" selected" if current else ""}">'
            f'<form action="{base}/select" method="post" class="history-select">'
            f'<button type="submit" title="{title}"{current}>{title}</button></form>'
            '<details class="chat-menu">'
            f'<summary aria-label="Options for {title}" title="Chat options">•••</summary>'
            '<div class="chat-menu-panel">'
            f'<form action="{base}/rename" method="post">'
            f'<label for="rename-{identifier}">Rename chat</label>'
            f'<input id="rename-{identifier}" name="title" value="{title}" '
            'maxlength="120" required>'
            '<button type="submit">Save name</button></form>'
            f'<form action="{base}/delete" method="post">'
            '<button type="submit" class="delete-chat">Delete chat</button></form>'
            "<small>Deleted chats can be restored from Trash.</small>"
            "</div></details></div>"
        )
    trash = (
        '<details class="chat-trash"><summary>Trash</summary>' + "".join(deleted) + "</details>"
        if deleted
        else ""
    )
    return (
        '<nav class="chat-history" aria-label="Chat history">'
        '<p class="history-label">Chat history</p>'
        + ("".join(active) or '<p class="history-empty">Your conversations will appear here.</p>')
        + trash
        + "</nav>"
    )
