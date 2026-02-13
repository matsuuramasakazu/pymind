import json
import re
from tkinter import filedialog, messagebox

class PersistenceHandler:
    """ファイルの保存・読み込みを管理するクラス"""
    def __init__(self, model, render_callback):
        self.model = model
        self.render_callback = render_callback
        self.current_file_path = None

    def on_save(self, event=None):
        if self.current_file_path:
            self._write_to_file(self.current_file_path, "保存が完了しました。")
        else:
            self.on_save_as(event)

    def on_save_as(self, event=None):
        default_name = self.model.root.text
        # 改行をスペースに置換
        default_name = default_name.replace("\n", " ").replace("\r", "")
        # マークアップタグを除去 (e.g. <b>...</b>)
        default_name = re.sub(r'<[^>]+>', '', default_name)
        # Windows等で禁止されている文字を除去
        default_name = re.sub(r'[\\/:*?"<>|]', '', default_name)
        
        if len(default_name) > 20:
            default_name = default_name[:20]
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            self._write_to_file(file_path, "別名で保存が完了しました。")

    def _write_to_file(self, file_path, success_msg):
        """共通のファイル書き込み処理"""
        try:
            data = self.model.save()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.current_file_path = file_path
            messagebox.showinfo("保存", f"{success_msg}\n{file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました: {e}")

    def on_open(self, event=None):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.model.load(data)
                self.current_file_path = file_path
                self.render_callback(root_node=self.model.root)
                messagebox.showinfo("読み込み", "読み込みが完了しました。")
            except Exception as e:
                messagebox.showerror("エラー", f"読み込みに失敗しました: {e}")
