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
