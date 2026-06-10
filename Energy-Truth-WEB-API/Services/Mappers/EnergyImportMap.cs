namespace Energy_Truth_WEB_API.Services.Mappers;

using CsvHelper.Configuration;
using Energy_Truth.Shared;
using Energy_Truth_WEB_API.Services;

public sealed class EnergyImportMap : ClassMap<EnergyImportDTO>
{
    public EnergyImportMap(Dictionary<string, string> userMapping, List<string> dateFormat)
    {
        if (userMapping.TryGetValue(nameof(EnergyImportDTO.Time), out var timeCol))
        {
            Map(m => m.Time).Name(timeCol)
                .TypeConverterOption.Format(dateFormat.ToArray());
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ImportT1), out var t1ImCol))
        {
            Map(m => m.ImportT1).Name(t1ImCol).TypeConverter<SafeDoubleConverter>();
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ImportT2), out var t2ImCol))
        {
            Map(m => m.ImportT2).Name(t2ImCol).TypeConverter<SafeDoubleConverter>();
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ExportT1), out var t1ExCol))
        {
            Map(m => m.ExportT1).Name(t1ExCol).TypeConverter<SafeDoubleConverter>();
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ExportT2), out var t2ExCol))
        {
            Map(m => m.ExportT2).Name(t2ExCol).TypeConverter<SafeDoubleConverter>();
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.L1MaxW), out var l1MWCol))
        {
            Map(m => m.L1MaxW).Name(l1MWCol).TypeConverter<SafeDoubleConverter>();
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.L2MaxW), out var l2MWCol))
        {
            Map(m => m.L2MaxW).Name(l2MWCol).TypeConverter<SafeDoubleConverter>();
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.L3MaxW), out var l3MWCol))
        {
            Map(m => m.L3MaxW).Name(l3MWCol).TypeConverter<SafeDoubleConverter>();
        }
    }
}