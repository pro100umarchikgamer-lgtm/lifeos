package app.lifeos.lifeos

import android.util.Xml
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.util.zip.ZipInputStream

/** Bounded, offline XLSX adapter. No formulas, macros, external links or source persistence. */
object StatementReader {
    fun sheets(bytes: ByteArray): Map<String, List<List<String>>> {
        val files = linkedMapOf<String, String>()
        var expanded = 0
        var members = 0
        ZipInputStream(ByteArrayInputStream(bytes)).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                require(++members <= 256)
                val name = entry.name
                require(!name.contains("..") && !name.startsWith("/") && !name.contains("vbaProject", true) && !name.startsWith("xl/externalLinks/"))
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = zip.read(buffer); if (count < 0) break
                    expanded += count; require(expanded <= 20 * 1024 * 1024)
                    if (name == "xl/sharedStrings.xml" || Regex("xl/worksheets/sheet[0-9]+\\.xml").matches(name)) output.write(buffer, 0, count)
                }
                if (output.size() > 0) {
                    val text = output.toString("UTF-8")
                    require(!Regex("<!DOCTYPE|<!ENTITY", RegexOption.IGNORE_CASE).containsMatchIn(text))
                    require(!files.containsKey(name)); files[name] = text
                }
            }
        }
        val strings = mutableListOf<String>()
        files["xl/sharedStrings.xml"]?.let { text ->
            val parser = parser(text); var value = StringBuilder(); var inItem = false
            while (parser.eventType != XmlPullParser.END_DOCUMENT) {
                if (parser.eventType == XmlPullParser.START_TAG && parser.name == "si") { value = StringBuilder(); inItem = true }
                if (parser.eventType == XmlPullParser.START_TAG && parser.name == "t" && inItem) value.append(parser.nextText())
                if (parser.eventType == XmlPullParser.END_TAG && parser.name == "si") { require(value.length <= 4000 && strings.size < 100000); strings.add(value.toString()); inItem = false }
                parser.next()
            }
        }
        val result = linkedMapOf<String, List<List<String>>>()
        for ((name, text) in files) {
            if (!name.startsWith("xl/worksheets/")) continue
            val rows = mutableListOf<List<String>>()
            val parser = parser(text); var row = mutableListOf<String>(); var column = 0; var type = ""
            while (parser.eventType != XmlPullParser.END_DOCUMENT) {
                if (parser.eventType == XmlPullParser.START_TAG) when (parser.name) {
                    "row" -> row = mutableListOf()
                    "c" -> {
                        val reference = parser.getAttributeValue(null, "r") ?: error("Missing cell reference")
                        column = 0
                        for (letter in reference.takeWhile { it in 'A'..'Z' }) column = column * 26 + (letter - 'A' + 1)
                        require(column in 1..100); while (row.size < column) row.add("")
                        type = parser.getAttributeValue(null, "t") ?: "n"
                    }
                    "f" -> error("Spreadsheet formulas are not accepted")
                    "v", "t" -> {
                        val value = parser.nextText(); require(value.length <= 4000 && column > 0)
                        row[column - 1] = if (type == "s") strings[value.toInt()] else value
                    }
                }
                if (parser.eventType == XmlPullParser.END_TAG && parser.name == "row") { require(rows.size < 10001); rows.add(row.toList()) }
                parser.next()
            }
            if (rows.size >= 2) result[name.substringAfterLast('/').removeSuffix(".xml")] = rows
        }
        require(result.isNotEmpty()); return result
    }
    fun statementXml(bytes: ByteArray): Map<String, List<List<String>>> {
        val text = bytes.toString(Charsets.UTF_8)
        require(!Regex("<!DOCTYPE|<!ENTITY", RegexOption.IGNORE_CASE).containsMatchIn(text))
        val rows = mutableListOf<List<String>>(listOf("date", "amount", "description", "currency"))
        val parser = parser(text); var values = mutableMapOf<String, String>()
        while (parser.eventType != XmlPullParser.END_DOCUMENT) {
            if (parser.eventType == XmlPullParser.START_TAG) when (parser.name) {
                "statement" -> Unit
                "transaction" -> values = mutableMapOf()
                "date", "amount", "description", "currency" -> { val key = parser.name; val value = parser.nextText(); require(value.length <= 4000); values[key] = value }
                else -> error("Unsupported statement XML schema")
            }
            if (parser.eventType == XmlPullParser.END_TAG && parser.name == "transaction") {
                require(rows.size < 10001); rows.add(listOf(values["date"] ?: "", values["amount"] ?: "", values["description"] ?: "", values["currency"] ?: ""))
            }
            parser.next()
        }
        require(rows.size > 1); return mapOf("statement" to rows)
    }
    private fun parser(text: String): XmlPullParser = Xml.newPullParser().apply {
        setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, false)
        setInput(text.reader())
    }
}
