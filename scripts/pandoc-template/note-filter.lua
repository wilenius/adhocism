-- Lua filter: converts [note: ...] in Markdown to \marginnote{...} in LaTeX
-- Place in same directory as template

function Note(elem)
  -- This handles inline [note: ...] pattern at the RawInline level
  -- We handle it in Str + Inlines instead
  return elem
end

-- Walk all inline elements and find [note: ...] patterns
function Inlines(inlines)
  local result = pandoc.Inlines({})
  local i = 1
  while i <= #inlines do
    local elem = inlines[i]
    
    -- Check for pattern: Str"[note:" ... Str"]"
    if elem.t == "Str" and elem.text:match("^%[note:") then
      -- Collect content until closing "]"
      local note_content = elem.text:gsub("^%[note:%s*", "")
      local j = i + 1
      local found_end = false
      
      if note_content:match("%]$") then
        note_content = note_content:gsub("%]$", "")
        found_end = true
        j = i
      else
        while j <= #inlines do
          if inlines[j].t == "Str" and inlines[j].text:match("%]$") then
            note_content = note_content .. " " .. inlines[j].text:gsub("%]$", "")
            found_end = true
            break
          elseif inlines[j].t == "Space" then
            note_content = note_content .. " "
          elseif inlines[j].t == "Str" then
            note_content = note_content .. inlines[j].text
          else
            note_content = note_content .. pandoc.utils.stringify(inlines[j])
          end
          j = j + 1
        end
      end
      
      if found_end then
        if FORMAT:match("latex") or FORMAT:match("pdf") then
          result:insert(pandoc.RawInline("latex", "\\marginnote{" .. note_content .. "}"))
        else
          result:insert(pandoc.Str("[note: " .. note_content .. "]"))
        end
        i = j + 1
      else
        result:insert(elem)
        i = i + 1
      end
    else
      result:insert(elem)
      i = i + 1
    end
  end
  return result
end

-- Promote headings so the shallowest one becomes \section. Pages put their
-- title in front matter and start body headings at ##, which pandoc would map
-- to \subsection, pushing ### to \subsubsection — undefined in tufte-handout.
function Pandoc(doc)
  local min_level = nil
  doc.blocks:walk({
    Header = function(h)
      if not min_level or h.level < min_level then min_level = h.level end
    end
  })
  if min_level and min_level > 1 then
    local shift = min_level - 1
    doc.blocks = doc.blocks:walk({
      Header = function(h)
        h.level = h.level - shift
        return h
      end
    })
  end
  return doc
end

local function is_latex()
  return FORMAT:match("latex") or FORMAT:match("pdf")
end

local function to_latex(inlines)
  return pandoc.write(pandoc.Pandoc({pandoc.Plain(inlines)}), "latex"):gsub("%s+$", "")
end

-- "### litreview – finding anthropological literature": set the name as the
-- heading and the part after the dash as an italic gloss beneath it, so the
-- names are what the eye catches when scanning a catalogue. The PDF bookmark
-- keeps the full text.
function Header(h)
  if not is_latex() then return nil end
  for i, el in ipairs(h.content) do
    if el.t == "Str" and (el.text == "–" or el.text == "—") and i > 1 then
      local head = pandoc.Inlines({})
      local gloss = pandoc.Inlines({})
      for k = 1, i - 1 do head:insert(h.content[k]) end
      for k = i + 1, #h.content do gloss:insert(h.content[k]) end
      while #head > 0 and head[#head].t == "Space" do head:remove(#head) end
      while #gloss > 0 and gloss[1].t == "Space" do gloss:remove(1) end
      if #gloss == 0 then return nil end
      head:insert(pandoc.RawInline("latex",
        "\\texorpdfstring{\\headinggloss{" .. to_latex(gloss) .. "}}{ – " ..
        pandoc.utils.stringify(gloss):gsub("[\\{}#%%&_^~$]", "") .. "}"))
      h.content = head
      return h
    end
  end
  return nil
end

-- "**Question:** Where have I…" — a bold label opening a paragraph becomes a
-- letterspaced small-caps run-in label (\runinlabel in sidenote.tex).
function Para(p)
  if not is_latex() then return nil end
  local first = p.content[1]
  if first and first.t == "Strong" then
    local label = pandoc.utils.stringify(first)
    if label:match(":$") and #label <= 40 then
      label = label:gsub(":$", "")
      p.content:remove(1)
      while #p.content > 0 and p.content[1].t == "Space" do p.content:remove(1) end
      p.content:insert(1, pandoc.RawInline("latex",
        "\\runinlabel{" .. to_latex(pandoc.Inlines({pandoc.Str(label)})) .. "}"))
      return p
    end
  end
  return nil
end
