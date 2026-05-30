namespace Energy_Truth_WEB_API.Services.Mappers;

using CsvHelper.Configuration;
using Energy_Truth.Shared;
using Energy_Truth_WEB_API.Services;

public sealed class EnergyImportMap : ClassMap<EnergyImportDTO> //sealed omdat we niet willen dat iemand deze map nog verder uitbreidt, en ClassMap omdat dit de basis is voor CsvHelper mapping
{
    public EnergyImportMap(Dictionary<string, string> userMapping, List<string> dateFormat) // Wanneer de mapper aangeroepen wordt dient de mapping van de gebruiker meegestuurd te worden. string 1 is de property naam van EnergyImportDTO, string 2 is de kolomnaam in het CSV bestand.
    {
        if (userMapping.TryGetValue(nameof(EnergyImportDTO.Time), out var timeCol)) // Er wordt geprobeerd om een waarde uit de userMapping te halen met als key de naam van de property in EnergyImportDTO. Als dit lukt, wordt de kolomnaam opgeslagen in timeCol.
        {
            Map(m => m.Time).Name(timeCol)
                .TypeConverterOption.Format(dateFormat.ToArray());  //verschillende time formats zijn hiermee toegestaan.
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ImportT1), out var t1ImCol)) // Hetzelfde gebeurt hier voor ImportT1, en de rest van de properties.
        {
            Map(m => m.ImportT1).Name(t1ImCol);
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ImportT2), out var t2ImCol))
        {
            Map(m => m.ImportT2).Name(t2ImCol);
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ExportT1), out var t1ExCol))
        {
            Map(m => m.ExportT1).Name(t1ExCol);
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.ExportT2), out var t2ExCol))
        {
            Map(m => m.ExportT2).Name(t2ExCol);
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.L1MaxW), out var l1MWCol))
        {
            Map(m => m.L1MaxW).Name(l1MWCol);
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.L2MaxW), out var l2MWCol))
        {
            Map(m => m.L2MaxW).Name(l2MWCol);
        }

        if (userMapping.TryGetValue(nameof(EnergyImportDTO.L3MaxW), out var l3MWCol))
        {
            Map(m => m.L3MaxW).Name(l3MWCol);
        }
    }
}
