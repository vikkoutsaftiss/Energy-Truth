namespace Energy_Truth_WEB_API.Services.Mappers;

using CsvHelper;
using CsvHelper.Configuration;
using CsvHelper.TypeConversion;
using System.Globalization;

public class SafeDoubleConverter : DoubleConverter
{
    public override object ConvertFromString(string text, IReaderRow row, MemberMapData memberMapData)
    {
        if (string.IsNullOrWhiteSpace(text)) return null;

        if (double.TryParse(text, NumberStyles.Any, CultureInfo.InvariantCulture, out var result))
            return result;

        if (double.TryParse(text, NumberStyles.Any, new CultureInfo("nl-NL"), out var nlResult))
            return nlResult;

        return null;
    }
}