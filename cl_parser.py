import re

class AdvancedParser:
    @staticmethod
    def inverse(alg_str):
        """求公式的逆运算"""
        if not alg_str.strip(): return ""
        moves = alg_str.split()
        inv = []
        for m in reversed(moves):
            if m.endswith("'") or m.endswith("’"): 
                inv.append(m[:-1])
            elif m.endswith("2"): 
                inv.append(m)  
            elif m.endswith("3"): 
                inv.append(m[:-1] + "'")
            else: 
                inv.append(m + "'")
        return " ".join(inv)

    @classmethod
    def _expand(cls, inner, mod):
        """展开重复/逆修饰：mod 可为 ''、数字、'、' 数字+'（如 3'）。"""
        if not mod:
            return inner
        if mod.endswith("'"):
            base = mod[:-1]
            seq = " ".join([inner] * int(base)) if base else inner
            return cls.inverse(seq)
        if mod.isdigit():
            return " ".join([inner] * int(mod))
        return inner

    @classmethod
    def parse(cls, alg):
        """核心解析方法"""
        alg = alg.replace("’", "'").replace("，", ",").replace("：", ":")
        alg = re.sub(r'(?<=[URFDLB2\'])(?=[URFDLB])', ' ', alg)
        
        while True:
            # 1. 剥离圆括号 ( ... )
            m_paren = re.search(r'\(([^()\[\]]+)\)(\d*\'?)?', alg)
            if m_paren:
                inner, mod = m_paren.group(1).strip(), m_paren.group(2) or ""
                alg = alg[:m_paren.start()] + " " + cls._expand(inner, mod) + " " + alg[m_paren.end():]
                continue

            # 2. 剥离方括号 [ ... ] (交换子或共轭)
            m_bracket = re.search(r'\[([^()\[\]]+)\](\d*\'?)?', alg)
            if m_bracket:
                inner, mod = m_bracket.group(1).strip(), m_bracket.group(2) or ""
                
                if ':' in inner:
                    setup, core = [p.strip() for p in inner.split(':', 1)]
                    expanded = f"{setup} {core} {cls.inverse(setup)}"
                elif ',' in inner:
                    parts = [p.strip() for p in inner.split(',', 1)]
                    expanded = f"{parts[0]} {parts[1]} {cls.inverse(parts[0])} {cls.inverse(parts[1])}" if len(parts) == 2 else inner
                else:
                    expanded = inner

                res = cls._expand(expanded, mod)
                alg = alg[:m_bracket.start()] + " " + res + " " + alg[m_bracket.end():]
                continue

            # 3. 裸共轭 A: B
            if ':' in alg:
                setup, core = [p.strip() for p in alg.split(':', 1)]
                alg = f"{setup} {core} {cls.inverse(setup)}"
                continue

            break

        return " ".join(alg.split())