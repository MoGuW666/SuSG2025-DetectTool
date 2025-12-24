from __future__ import annotations
from typing import Iterator, Tuple
import os
import time


def follow_file(
    path: str,
    *,
    start_at_end: bool = True,
    poll_interval: float = 0.2,
    yield_heartbeat: bool = False,
) -> Iterator[Tuple[int, str]]:
    """
    Follow a text file like `tail -f`.
    Yields (line_no, line). For monitor mode, line_no is:
      - actual line number if start_at_end=False (read from beginning)
      - incremental counter starting from 1 if start_at_end=True (new lines only)
    Handles simple truncation/rotation by reopening when inode changes or file shrinks.
    """
    line_no = 0

    def _open():
        return open(path, "r", encoding="utf-8", errors="replace")

    f = _open()
    try:
        st = os.stat(path)
        inode = st.st_ino

        if start_at_end:
            f.seek(0, os.SEEK_END)
            # 只跟随新增行，不去数历史行（避免大文件开销）
            line_no = 0
        else:
            f.seek(0, os.SEEK_SET)
            line_no = 0

        while True:
            line = f.readline()
            if line:
                line_no += 1
                yield line_no, line
                continue

            # 没有新行：检查是否被截断/轮转
            time.sleep(poll_interval)
            if yield_heartbeat:
                yield 0, ""
            try:
                st2 = os.stat(path)
            except FileNotFoundError:
                # 文件暂时不存在（比如轮转瞬间），继续等
                continue

            if st2.st_ino != inode or st2.st_size < f.tell():
                # 轮转/截断：重开文件
                try:
                    f.close()
                except Exception:
                    pass
                f = _open()
                inode = st2.st_ino
                if start_at_end:
                    f.seek(0, os.SEEK_END)
                    line_no = 0
                else:
                    f.seek(0, os.SEEK_SET)
                    line_no = 0

    finally:
        try:
            f.close()
        except Exception:
            pass


