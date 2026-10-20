package syntax

import (
	"bytes"
	"fmt"
	"go/scanner"
	"go/token"
	"regexp"
	"strings"
)

type tok struct {
	pos, end int
	tok      token.Token
	lit      string
}

type parenKind int

const (
	kParen  parenKind = iota // grouping parentheses
	kCall                    // argument list of a call
	kSig                     // parameter list of a function literal or type
	kSigDef                  // parameter list of a function declaration (defaults allowed)
	kRecv                    // receiver list
	kBrack                   // [ ]
	kBrace                   // { }
)

type rewriter struct {
	f     *File
	src   []byte
	toks  []tok
	match []int // index of the matching bracket
	out   bytes.Buffer
	cur   int // source offset up to which the source has been consumed
	stack []parenKind
	errs  ErrorList

	nextParen  parenKind
	haveNext   bool
	pendingExt bool
	matchID    int
}

func newRewriter(f *File) (*rewriter, error) {
	r := &rewriter{f: f, src: f.Src}
	fset := token.NewFileSet()
	tf := fset.AddFile(f.Path, -1, len(f.Src))
	var s scanner.Scanner
	var serr scanner.ErrorList
	s.Init(tf, f.Src, func(pos token.Position, msg string) { serr.Add(pos, msg) }, 0)
	for {
		p, t, lit := s.Scan()
		off := tf.Offset(p)
		end := off
		switch {
		case t == token.EOF:
		case t == token.SEMICOLON && lit != ";":
		case t == token.STRING && strings.HasPrefix(lit, "`"):
			if i := bytes.IndexByte(f.Src[off+1:], '`'); i >= 0 {
				end = off + i + 2
			}
		case lit != "":
			end = off + len(lit)
		default:
			end = off + len(t.String())
		}
		r.toks = append(r.toks, tok{off, end, t, lit})
		if t == token.EOF {
			break
		}
	}
	if len(serr) > 0 {
		var errs ErrorList
		for _, e := range serr {
			errs = append(errs, &Error{Pos: e.Pos, Msg: e.Msg})
		}
		return nil, errs
	}
	r.match = make([]int, len(r.toks))
	var st []int
	for i, t := range r.toks {
		r.match[i] = -1
		switch t.tok {
		case token.LPAREN, token.LBRACK, token.LBRACE:
			st = append(st, i)
		case token.RPAREN, token.RBRACK, token.RBRACE:
			if len(st) > 0 {
				o := st[len(st)-1]
				st = st[:len(st)-1]
				r.match[o], r.match[i] = i, o
			}
		}
	}
	return r, nil
}

func (r *rewriter) errorf(off int, format string, args ...any) {
	r.errs = append(r.errs, &Error{Pos: r.f.origPosition(off), Msg: fmt.Sprintf(format, args...)})
}

// copyTo copies the original source up to offset off.
func (r *rewriter) copyTo(off int) {
	if off <= r.cur {
		return
	}
	r.f.Map.add(r.out.Len(), r.cur, false)
	r.out.Write(r.src[r.cur:off])
	r.cur = off
}

// gen emits synthetic text that maps to the original offset orig.
func (r *rewriter) gen(s string, orig int) {
	if s == "" {
		return
	}
	r.f.Map.add(r.out.Len(), orig, true)
	r.out.WriteString(s)
	r.f.Map.add(r.out.Len(), r.cur, false)
}

// skipTo drops the original source up to off but keeps its line breaks.
func (r *rewriter) skipTo(off int) {
	if off <= r.cur {
		return
	}
	n := bytes.Count(r.src[r.cur:off], []byte("\n"))
	from := r.cur
	r.cur = off
	r.gen(strings.Repeat("\n", n), from)
	r.f.Map.add(r.out.Len(), r.cur, false)
}

// emit copies token k (and the gap before it) and returns the rewritten
// offset at which the token starts.
func (r *rewriter) emit(k int) int {
	t := r.toks[k]
	r.copyTo(t.pos)
	off := r.out.Len()
	r.copyTo(t.end)
	return off
}

func (r *rewriter) at(k int) token.Token {
	if k < 0 || k >= len(r.toks) {
		return token.EOF
	}
	return r.toks[k].tok
}

func (r *rewriter) isArrow(k int) bool {
	return r.at(k) == token.ASSIGN && r.at(k+1) == token.GTR && r.toks[k+1].pos == r.toks[k].pos+1
}

func (r *rewriter) identAt(k int, name string) bool {
	return r.at(k) == token.IDENT && r.toks[k].lit == name
}

func (r *rewriter) run() {
	r.process(0, len(r.toks)-1)
	r.copyTo(len(r.src))
}

func (r *rewriter) push(k parenKind) { r.stack = append(r.stack, k) }

func (r *rewriter) pop() {
	if len(r.stack) > 0 {
		r.stack = r.stack[:len(r.stack)-1]
	}
}

func (r *rewriter) top() parenKind {
	if len(r.stack) == 0 {
		return -1
	}
	return r.stack[len(r.stack)-1]
}

// process rewrites tokens in [i, j).
func (r *rewriter) process(i, j int) {
	for k := i; k < j; {
		k = r.step(k, j)
	}
}

func (r *rewriter) step(k, j int) int {
	t := r.toks[k]
	toplevel := len(r.stack) == 0
	switch {
	case toplevel && r.identAt(k, "enum") && r.at(k+1) == token.IDENT:
		return r.enumDecl(k)
	case toplevel && r.identAt(k, "ext") && r.at(k+1) == token.FUNC:
		r.copyTo(t.pos)
		r.skipTo(r.toks[k+1].pos)
		r.pendingExt = true
		return k + 1
	case t.tok == token.FUNC:
		return r.funcHeader(k, toplevel)
	case r.identAt(k, "match") && r.at(k-1) != token.PERIOD && r.isMatch(k):
		return r.matchExpr(k)
	case t.tok == token.IDENT && k+1 < j && r.isArrow(k+1),
		t.tok == token.LPAREN && r.match[k] > 0 && r.match[k]+1 < j && r.isArrow(r.match[k]+1) && !r.callParen(k):
		return r.lambda(k)
	case t.tok == token.IDENT && r.at(k+1) == token.COLON && r.top() == kCall &&
		(r.at(k-1) == token.LPAREN || r.at(k-1) == token.COMMA):
		return r.namedArg(k)
	case t.tok == token.ASSIGN && r.top() == kSigDef && !r.isArrow(k):
		return r.defaultParam(k)
	case t.tok.IsKeyword() && r.at(k-1) == token.PERIOD:
		r.copyTo(t.pos)
		r.cur = t.end
		r.gen(KeywordPfx+t.lit, t.pos)
		return k + 1
	}
	switch t.tok {
	case token.LPAREN:
		kind := kParen
		if r.haveNext {
			kind, r.haveNext = r.nextParen, false
		} else {
			switch r.at(k - 1) {
			case token.IDENT, token.RPAREN, token.RBRACK:
				kind = kCall
			}
		}
		r.push(kind)
	case token.LBRACK:
		r.push(kBrack)
	case token.LBRACE:
		r.push(kBrace)
	case token.RPAREN, token.RBRACK, token.RBRACE:
		r.pop()
	}
	r.emit(k)
	return k + 1
}

// callParen reports whether the parenthesis at k opens an argument list.
func (r *rewriter) callParen(k int) bool {
	switch r.at(k - 1) {
	case token.IDENT, token.RPAREN, token.RBRACK, token.RBRACE, token.STRING:
		return true
	}
	return false
}

func (r *rewriter) funcHeader(k int, toplevel bool) int {
	off := r.emit(k)
	if r.pendingExt {
		r.f.ExtFuncs[off] = true
		r.pendingExt = false
	}
	k++
	if !toplevel {
		if r.at(k) == token.LPAREN {
			r.nextParen, r.haveNext = kSig, true
		}
		return k
	}
	hasRecv := false
	if r.at(k) == token.LPAREN {
		hasRecv = true
		end := r.match[k]
		r.nextParen, r.haveNext = kRecv, true
		r.process(k, end+1)
		k = end + 1
	}
	var nameOff int
	if t := r.toks[k]; t.tok.IsKeyword() {
		r.copyTo(t.pos)
		nameOff = r.out.Len()
		r.cur = t.end
		r.gen(KeywordPfx+t.lit, t.pos)
		k++
	} else if t.tok == token.IDENT {
		nameOff = r.emit(k)
		k++
	}
	if hasRecv && r.at(k) == token.LBRACK && r.match[k] > 0 {
		end := r.match[k]
		r.f.MethodTParams[nameOff] = string(r.src[r.toks[k].pos:r.toks[end].end])
		r.copyTo(r.toks[k].pos)
		r.skipTo(r.toks[end].end)
		k = end + 1
	}
	if r.at(k) == token.LPAREN {
		r.nextParen, r.haveNext = kSigDef, true
	}
	return k
}

// exprEnd returns the index of the first token at nesting depth 0 that ends
// an expression starting at k.
func (r *rewriter) exprEnd(k int, stops ...token.Token) int {
	depth := 0
	for ; k < len(r.toks); k++ {
		t := r.toks[k].tok
		if depth == 0 {
			for _, s := range stops {
				if t == s {
					return k
				}
			}
		}
		switch t {
		case token.EOF:
			return k
		case token.LPAREN, token.LBRACK, token.LBRACE:
			depth++
		case token.RPAREN, token.RBRACK, token.RBRACE:
			if depth == 0 {
				return k
			}
			depth--
		}
	}
	return k
}

func (r *rewriter) namedArg(k int) int {
	t := r.toks[k]
	end := r.exprEnd(k+2, token.COMMA)
	r.copyTo(t.pos)
	r.cur = r.toks[k+1].end
	r.gen(fmt.Sprintf("%s(%q, ", NamedFunc, t.lit), t.pos)
	r.process(k+2, end)
	r.copyTo(r.toks[end-1].end)
	r.gen(")", r.toks[end-1].end)
	return end
}

func (r *rewriter) defaultParam(k int) int {
	t := r.toks[k]
	end := r.exprEnd(k+1, token.COMMA)
	if end == k+1 {
		r.errorf(t.pos, "missing default value")
		return end
	}
	r.copyTo(t.pos)
	r.f.Defaults[r.out.Len()] = string(r.src[r.toks[k+1].pos:r.toks[end-1].end])
	r.skipTo(r.toks[end-1].end)
	return end
}

func (r *rewriter) lambda(k int) int {
	t := r.toks[k]
	var params string
	arrow := k + 1
	if t.tok == token.IDENT {
		params = t.lit + " " + InferType
	} else {
		rp := r.match[k]
		arrow = rp + 1
		var parts [][]tok
		var cur []tok
		depth := 0
		for i := k + 1; i < rp; i++ {
			tt := r.toks[i]
			switch tt.tok {
			case token.LPAREN, token.LBRACK, token.LBRACE:
				depth++
			case token.RPAREN, token.RBRACK, token.RBRACE:
				depth--
			}
			if tt.tok == token.COMMA && depth == 0 {
				parts = append(parts, cur)
				cur = nil
				continue
			}
			cur = append(cur, tt)
		}
		if len(cur) > 0 {
			parts = append(parts, cur)
		}
		typed := false
		for _, p := range parts {
			if p[0].tok != token.IDENT {
				r.errorf(p[0].pos, "invalid parameter in short function")
				return rp + 1
			}
			if len(p) > 1 {
				typed = true
			}
		}
		if typed {
			params = string(r.src[r.toks[k+1].pos:r.toks[rp].pos])
		} else {
			var names []string
			for _, p := range parts {
				names = append(names, p[0].lit+" "+InferType)
			}
			params = strings.Join(names, ", ")
		}
	}
	body := arrow + 2
	r.copyTo(t.pos)
	r.cur = r.toks[arrow+1].end
	if r.at(body) == token.LBRACE {
		r.gen("func("+params+") "+InferType+" ", t.pos)
		end := r.match[body]
		r.process(body, end+1)
		return end + 1
	}
	end := r.exprEnd(body, token.COMMA, token.SEMICOLON, token.COLON)
	if end == body {
		r.errorf(r.toks[arrow].pos, "missing body of short function")
		return end
	}
	r.gen("func("+params+") "+InferType+" { return", t.pos)
	r.process(body, end)
	r.copyTo(r.toks[end-1].end)
	r.gen(" }", r.toks[end-1].end)
	return end
}

func (r *rewriter) isMatch(k int) bool {
	depth := 0
	s := k + 1
	for ; s < len(r.toks); s++ {
		switch t := r.toks[s].tok; t {
		case token.LPAREN, token.LBRACK:
			depth++
		case token.RPAREN, token.RBRACK:
			depth--
			if depth < 0 {
				return false
			}
		case token.LBRACE:
			if depth == 0 {
				goto found
			}
			depth++
		case token.RBRACE:
			depth--
		case token.SEMICOLON, token.COMMA, token.ASSIGN, token.DEFINE, token.COLON, token.EOF:
			if depth == 0 {
				return false
			}
		}
	}
	return false
found:
	if s == k+1 || r.match[s] < 0 {
		return false
	}
	i := s + 1
	for r.at(i) == token.SEMICOLON {
		i++
	}
	depth = 0
	for ; i < r.match[s]; i++ {
		if depth == 0 && r.isArrow(i) {
			return true
		}
		switch r.toks[i].tok {
		case token.LPAREN, token.LBRACK, token.LBRACE:
			depth++
		case token.RPAREN, token.RBRACK, token.RBRACE:
			depth--
		case token.SEMICOLON, token.COMMA:
			if depth == 0 {
				return false
			}
		}
	}
	return false
}

func (r *rewriter) matchExpr(k int) int {
	t := r.toks[k]
	lb := k + 1
	for depth := 0; ; lb++ {
		tt := r.toks[lb].tok
		if tt == token.LBRACE && depth == 0 {
			break
		}
		switch tt {
		case token.LPAREN, token.LBRACK, token.LBRACE:
			depth++
		case token.RPAREN, token.RBRACK, token.RBRACE:
			depth--
		}
	}
	rb := r.match[lb]
	// a match at the start of a statement is a match statement: its arms
	// may be simple statements
	stmt := false
	switch r.at(k - 1) {
	case token.SEMICOLON, token.LBRACE, token.COLON:
		stmt = true
	}
	r.matchID++
	m := &MatchDecl{ID: r.matchID, Pos: r.f.origPosition(t.pos)}
	r.f.Matches[m.ID] = m

	r.copyTo(t.pos)
	r.cur = t.end
	r.gen(fmt.Sprintf("%s(%d, (", MatchFunc, m.ID), t.pos)
	r.process(k+1, lb)
	r.copyTo(r.toks[lb-1].end)
	r.gen("),", r.toks[lb-1].end)
	r.cur = r.toks[lb].end

	i := lb + 1
	for {
		for r.at(i) == token.SEMICOLON || r.at(i) == token.COMMA {
			i++
		}
		if i >= rb {
			break
		}
		arm := &ArmDecl{Pos: r.f.origPosition(r.toks[i].pos)}
		// pattern
		ps := i
		depth := 0
		for ; i < rb; i++ {
			if depth == 0 && (r.isArrow(i) || r.at(i) == token.IF) {
				break
			}
			switch r.toks[i].tok {
			case token.LPAREN, token.LBRACK, token.LBRACE:
				depth++
			case token.RPAREN, token.RBRACK, token.RBRACE:
				depth--
			}
		}
		if i >= rb || i == ps {
			r.errorf(r.toks[ps].pos, "expected pattern followed by => in match arm")
			return rb + 1
		}
		arm.Patterns = r.patterns(ps, i)
		r.skipTo(r.toks[ps].pos)
		r.cur = r.toks[i-1].end
		if r.at(i) == token.IF {
			gs := i + 1
			ge := gs
			for ge < rb && !r.isArrow(ge) {
				ge++
			}
			if ge >= rb || ge == gs {
				r.errorf(r.toks[i].pos, "expected guard expression followed by =>")
				return rb + 1
			}
			arm.HasGuard = true
			r.gen(" func() bool { return", r.toks[i].pos)
			r.cur = r.toks[i].end
			r.process(gs, ge)
			r.copyTo(r.toks[ge-1].end)
			r.gen(" },", r.toks[ge-1].end)
			i = ge
		} else {
			r.gen(" nil,", r.toks[i].pos)
		}
		// i is at =>
		r.cur = r.toks[i+1].end
		bs := i + 2
		if r.at(bs) == token.LBRACE {
			arm.Block = true
			r.gen(" func()", r.toks[i].pos)
			end := r.match[bs]
			r.process(bs, end+1)
			r.gen(",", r.toks[end].end)
			i = end + 1
		} else {
			be := r.exprEnd(bs, token.COMMA, token.SEMICOLON)
			if be == bs {
				r.errorf(r.toks[i].pos, "missing arm body")
				return rb + 1
			}
			if stmt {
				arm.Block = true
				r.gen(" func() {", r.toks[i].pos)
			} else {
				r.gen(" func() any { return", r.toks[i].pos)
			}
			r.process(bs, be)
			r.copyTo(r.toks[be-1].end)
			r.gen(" },", r.toks[be-1].end)
			i = be
		}
		m.Arms = append(m.Arms, arm)
	}
	r.skipTo(r.toks[rb].pos)
	r.cur = r.toks[rb].end
	r.gen(")", r.toks[rb].pos)
	if len(m.Arms) == 0 {
		r.errorf(t.pos, "match without arms")
	}
	return rb + 1
}

func (r *rewriter) patterns(i, j int) []*PatternDecl {
	var alts [][2]int
	start := i
	depth := 0
	for k := i; k < j; k++ {
		switch r.toks[k].tok {
		case token.LPAREN, token.LBRACK, token.LBRACE:
			depth++
		case token.RPAREN, token.RBRACK, token.RBRACE:
			depth--
		case token.OR:
			if depth == 0 {
				alts = append(alts, [2]int{start, k})
				start = k + 1
			}
		}
	}
	alts = append(alts, [2]int{start, j})
	var out []*PatternDecl
	for _, a := range alts {
		s, e := a[0], a[1]
		if s >= e {
			r.errorf(r.toks[i].pos, "empty pattern")
			continue
		}
		p := &PatternDecl{Pos: r.f.origPosition(r.toks[s].pos), Expr: string(r.src[r.toks[s].pos:r.toks[e-1].end])}
		out = append(out, p)
		if e-s == 1 && r.identAt(s, "_") {
			p.Wildcard = true
			continue
		}
		k := s
		if r.at(k) != token.IDENT {
			continue
		}
		name := r.toks[k].lit
		k++
		qual := ""
		if r.at(k) == token.PERIOD && r.at(k+1) == token.IDENT && k+1 < e {
			qual, name = name, r.toks[k+1].lit
			k += 2
		}
		if k == e {
			p.Qual, p.Name = qual, name
			continue
		}
		if r.at(k) == token.LPAREN && r.match[k] == e-1 {
			p.Qual, p.Name, p.Parens = qual, name, true
			for b := k + 1; b < e-1; b++ {
				if r.at(b) != token.IDENT || (r.at(b+1) != token.COMMA && b+1 != e-1) {
					r.errorf(r.toks[b].pos, "variant pattern binders must be identifiers or _")
					break
				}
				p.Binders = append(p.Binders, r.toks[b].lit)
				b++
			}
		}
	}
	return out
}

var reprRe = regexp.MustCompile(`//\s*gonext:repr\s+(\w+)`)

func (r *rewriter) enumDecl(k int) int {
	t := r.toks[k]
	prevEnd := 0
	if k > 0 {
		prevEnd = r.toks[k-1].end
	}
	e := &EnumDecl{Name: r.toks[k+1].lit, Pos: r.f.origPosition(t.pos)}
	if m := reprRe.FindSubmatch(r.src[prevEnd:t.pos]); m != nil {
		e.Repr = string(m[1])
	}
	i := k + 2
	if r.at(i) == token.LBRACK && r.match[i] > 0 {
		e.TParams = string(r.src[r.toks[i].pos:r.toks[r.match[i]].end])
		i = r.match[i] + 1
	}
	if r.at(i) != token.LBRACE || r.match[i] < 0 {
		r.errorf(r.toks[i].pos, "expected { after enum name")
		return i + 1
	}
	rb := r.match[i]
	for i++; i < rb; {
		switch r.at(i) {
		case token.SEMICOLON, token.COMMA:
			i++
			continue
		case token.IDENT:
		default:
			r.errorf(r.toks[i].pos, "expected variant name")
			return rb + 1
		}
		v := &VariantDecl{Name: r.toks[i].lit, Pos: r.f.origPosition(r.toks[i].pos)}
		i++
		if r.at(i) == token.LPAREN && r.match[i] > 0 {
			v.Params = string(r.src[r.toks[i].pos:r.toks[r.match[i]].end])
			i = r.match[i] + 1
		}
		e.Variants = append(e.Variants, v)
	}
	if len(e.Variants) == 0 {
		r.errorf(t.pos, "enum %s has no variants", e.Name)
	}
	r.copyTo(t.pos)
	e.Offset = r.out.Len()
	r.skipTo(r.toks[rb].end)
	r.f.Enums = append(r.f.Enums, e)
	return rb + 1
}
