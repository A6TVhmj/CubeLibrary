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
    def parse(cls, alg):
        """核心解析方法"""
        alg = alg.replace("’", "'").replace("，", ",").replace("：", ":")
        
        while True:
            # 1. 剥离圆括号 ( ... )
            m_paren = re.search(r'\(([^()\[\]]+)\)(\d*|\')', alg)
            if m_paren:
                inner, mod = m_paren.group(1).strip(), m_paren.group(2)
                res = cls.inverse(inner) if mod == "'" else " ".join([inner] * int(mod)) if mod.isdigit() else inner
                alg = alg[:m_paren.start()] + " " + res + " " + alg[m_paren.end():]
                continue

            # 2. 剥离方括号 [ ... ] (交换子或共轭)
            m_bracket = re.search(r'\[([^()\[\]]+)\](\d*|\')', alg)
            if m_bracket:
                inner, mod = m_bracket.group(1).strip(), m_bracket.group(2)
                
                if ':' in inner:
                    setup, core = [p.strip() for p in inner.split(':', 1)]
                    expanded = f"{setup} {core} {cls.inverse(setup)}"
                elif ',' in inner:
                    parts = [p.strip() for p in inner.split(',', 1)]
                    expanded = f"{parts[0]} {parts[1]} {cls.inverse(parts[0])} {cls.inverse(parts[1])}" if len(parts) == 2 else inner
                else:
                    expanded = inner

                res = cls.inverse(expanded) if mod == "'" else " ".join([expanded] * int(mod)) if mod.isdigit() else expanded
                alg = alg[:m_bracket.start()] + " " + res + " " + alg[m_bracket.end():]
                continue

            # 3. 裸共轭 A: B
            if ':' in alg:
                setup, core = [p.strip() for p in alg.split(':', 1)]
                alg = f"{setup} {core} {cls.inverse(setup)}"
                continue

            break

        return " ".join(alg.split())