import tkinter as tk
from typing import Dict, Optional
from models import Node

class GraphicsEngine:
    """tkinter.Canvas上での描画を管理するクラス"""
    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.node_items: Dict[str, int] = {}  # node_id -> canvas_item_id (rect)
        self.text_items: Dict[str, int] = {}  # node_id -> canvas_item_id (text)
        self.line_items: Dict[str, int] = {}  # node_id -> canvas_item_id (line connecting to parent)
        
        # デザイン設定
        self.node_bg = "#ffffff"
        self.node_outline = "#333333"
        self.root_bg = "#f0f0f0"
        self.text_color = "#000000"
        self.line_color = "#888888"
        self.font = ("Yu Gothic", 10)
        self.root_font = ("Yu Gothic", 12, "bold")

    def get_text_size(self, text: str, font, max_width: int = 150):
        """テキストの描画サイズを計算して返す"""
        # 仮のキャンバスアイテムでサイズを測定
        temp_id = self.canvas.create_text(
            0, 0, text=text, font=font, width=max_width
        )
        bbox = self.canvas.bbox(temp_id)
        self.canvas.delete(temp_id)
        if bbox:
            w = bbox[2] - bbox[0] + 20 # パディング
            h = bbox[3] - bbox[1] + 10
            return max(100, w), max(40, h)
        return 100, 40

    def draw_node(self, node: Node, is_selected: bool = False):
        x, y = node.x, node.y
        font = self.root_font if node.parent is None else self.font
        
        # テキストサイズに合わせてノードサイズを更新
        node.width, node.height = self.get_text_size(node.text, font)
        w, h = node.width, node.height
        
        bg = self.root_bg if node.parent is None else self.node_bg
        outline_width = 2 if is_selected else 1
        outline_color = "#0078d7" if is_selected else self.node_outline
        
        # 既存のアイテムを削除
        if node.id in self.node_items:
            self.canvas.delete(self.node_items[node.id])
        if node.id in self.text_items:
            self.canvas.delete(self.text_items[node.id])
            
        # ノード（矩形）の描画
        rect_id = self.canvas.create_rectangle(
            x - w/2, y - h/2, x + w/2, y + h/2,
            fill=bg, outline=outline_color, width=outline_width,
            tags=("node", node.id)
        )
        self.node_items[node.id] = rect_id
        
        # テキストの描画
        text_id = self.canvas.create_text(
            x, y, text=node.text, fill=self.text_color, font=font,
            width=150, justify="center", tags=("text", node.id)
        )
        self.text_items[node.id] = text_id
        
        # 親との接続線
        if node.parent:
            self.draw_connection(node)

    def draw_connection(self, node: Node):
        if not node.parent:
            return
            
        if node.id in self.line_items:
            self.canvas.delete(self.line_items[node.id])
            
        p = node.parent
        # ノードの方向に合わせた接続位置の計算
        direction = getattr(node, 'direction', 'right')
        if p.parent is None: # ルートの子の場合
            px = p.x + p.width/2 if direction == 'right' else p.x - p.width/2
            nx = node.x - node.width/2 if direction == 'right' else node.x + node.width/2
        else: # 孫以降の場合、親の方向を引き継ぐ
            # 親ノードがどちらにあるか
            parent_dir = 'right' if node.x > p.x else 'left'
            px = p.x + p.width/2 if parent_dir == 'right' else p.x - p.width/2
            nx = node.x - node.width/2 if parent_dir == 'right' else node.x + node.width/2

        line_id = self.canvas.create_line(
            px, p.y, nx, node.y,
            fill=self.line_color, width=1.5,
            smooth=True, tags=("line", node.id)
        )
        self.line_items[node.id] = line_id

    def clear(self):
        self.canvas.delete("all")
        self.node_items.clear()
        self.text_items.clear()
        self.line_items.clear()
