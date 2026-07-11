from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .models import Entry, FormatError

_MAGIC = bytes.fromhex("55 AA 88 81 02 00 60 00 55 AA 55 AA")
_ENTRY_BASE = 0x2400
_ENTRY_SIZE = 60

# Order is the confirmed order used by the local reference implementation.
_PINYIN = """a ai an ang ao ba bai ban bang bao bei ben beng bi bian biao bie bin bing bo bu ca cai can cang cao ce cen ceng cha chai chan chang chao che chen cheng chi chong chou chu chua chuai chuan chuang chui chun chuo ci cong cou cu cuan cui cun cuo da dai dan dang dao de dei den deng di dia dian diao die ding diu dong dou du duan dui dun duo e ei en eng er fa fan fang fei fen feng fiao fo fou fu ga gai gan gang gao ge gei gen geng gong gou gu gua guai guan guang gui gun guo ha hai han hang hao he hei hen heng hong hou hu hua huai huan huang hui hun huo ji jia jian jiang jiao jie jin jing jiong jiu ju juan jue jun ka kai kan kang kao ke kei ken keng kong kou ku kua kuai kuan kuang kui kun kuo la lai lan lang lao le lei leng li lia lian liang liao lie lin ling liu lo long lou lu luan lue lun luo lv ma mai man mang mao me mei men meng mi mian miao mie min ming miu mo mou mu na nai nan nang nao ne nei nen neng ni nian niang niao nie nin ning niu nong nou nu nuan nue nun nuo nv o ou pa pai pan pang pao pei pen peng pi pian piao pie pin ping po pou pu qi qia qian qiang qiao qie qin qing qiong qiu qu quan que qun ran rang rao re ren reng ri rong rou ru rua ruan rui run ruo sa sai san sang sao se sen seng sha shai shan shang shao she shei shen sheng shi shou shu shua shuai shuan shuang shui shun shuo si song sou su suan sui sun suo ta tai tan tang tao te tei teng ti tian tiao tie ting tong tou tu tuan tui tun tuo wa wai wan wang wei wen weng wo wu xi xia xian xiang xiao xie xin xing xiong xiu xu xuan xue xun ya yan yang yao ye yi yin ying yo yong you yu yuan yue yun za zai zan zang zao ze zei zen zeng zha zhai zhan zhang zhao zhe zhei zhen zheng zhi zhong zhou zhu zhua zhuai zhuan zhuang zhui zhun zhuo zi zong zou zu zuan zui zun zuo""".split()


@dataclass(frozen=True)
class SelfStudyDat:
    raw: bytes
    timestamp: int
    entries: tuple[Entry, ...]

    @classmethod
    def read(cls, path: str | Path) -> "SelfStudyDat":
        raw = Path(path).read_bytes()
        if len(raw) < _ENTRY_BASE or raw[:12] != _MAGIC:
            raise FormatError("not a supported ChsPinyinUDL.dat")
        count = struct.unpack_from("<Q", raw, 0x0C)[0]
        timestamp = struct.unpack_from("<I", raw, 0x14)[0]
        if count > 20000 or _ENTRY_BASE + count * _ENTRY_SIZE > len(raw):
            raise FormatError("entry count is out of bounds")
        entries: list[Entry] = []
        for index in range(count):
            offset = _ENTRY_BASE + index * _ENTRY_SIZE
            length = raw[offset + 10]
            if not 1 <= length <= 12 or 12 + length * 4 > _ENTRY_SIZE:
                raise FormatError(f"entry {index} has invalid length")
            word = raw[offset + 12:offset + 12 + length * 2].decode("utf-16le")
            indices = struct.unpack_from(f"<{length}h", raw, offset + 12 + length * 2)
            try:
                codes = tuple(_PINYIN[value] for value in indices)
            except IndexError as exc:
                raise FormatError(f"entry {index} has invalid pinyin index") from exc
            entries.append(Entry(word=word, codes=codes))
        return cls(raw, timestamp, tuple(entries))

    def write_unchanged(self, path: str | Path) -> None:
        Path(path).write_bytes(self.raw)

    @classmethod
    def create(cls, entries: tuple[Entry, ...], *, timestamp: int = 0x31E3BB79) -> "SelfStudyDat":
        if len(entries) > 20000:
            raise FormatError("self-study dictionary supports at most 20000 entries")
        result = bytearray(_ENTRY_BASE + len(entries) * _ENTRY_SIZE)
        result[:12] = _MAGIC
        struct.pack_into("<Q", result, 0x0C, len(entries))
        struct.pack_into("<I", result, 0x14, timestamp)
        for index, entry in enumerate(entries):
            length = len(entry.word)
            if not 2 <= length <= 12 or len(entry.codes) != length:
                raise FormatError("self-study entries need 2-12 characters and one pinyin code per character")
            offset = _ENTRY_BASE + index * _ENTRY_SIZE
            # Confirmed structural fields. Unknown prefix bytes use the public reference defaults.
            struct.pack_into("<H", result, offset, index + 0x6D1B)
            result[offset + 2:offset + 4] = b"\x1A\x26"
            result[offset + 9] = 4
            result[offset + 10] = length
            result[offset + 11] = 0x5A
            result[offset + 12:offset + 12 + length * 2] = entry.word.encode("utf-16le")
            try:
                indices = tuple(_PINYIN.index(code.lower()) for code in entry.codes)
            except ValueError as exc:
                raise FormatError("unsupported pinyin syllable") from exc
            struct.pack_into(f"<{length}h", result, offset + 12 + length * 2, *indices)
        aligned = ((len(result) + 1023) // 1024) * 1024
        result.extend(b"\0" * (aligned - len(result)))
        return cls(bytes(result), timestamp, entries)

    def write(self, path: str | Path) -> None:
        Path(path).write_bytes(self.raw)
