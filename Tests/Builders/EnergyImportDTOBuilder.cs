using Energy_Truth.Shared;

public class EnergyImportDTOBuilder
{
    private DateTime _time = DateTime.Now;
    private double? _importT1 = 100;
    private double? _importT2 = 150;
    private double? _exportT1 = 50;
    private double? _exportT2 = 75;
    private int? _l1MaxW = 200;
    private int? _l2MaxW = 200;
    private int? _l3MaxW = 200;

    public EnergyImportDTOBuilder WithTime(DateTime time)
    {
        _time = time;
        return this;
    }

    public EnergyImportDTOBuilder WithImportT1(double value)
    {
        _importT1 = value;
        return this;
    }

    public EnergyImportDTOBuilder WithImportT2(double value)
    {
        _importT2 = value;
        return this;
    }

    public EnergyImportDTOBuilder WithExportT1(double value)
    {
        _exportT1 = value;
        return this;
    }

    public EnergyImportDTOBuilder WithExportT2(double value)
    {
        _exportT2 = value;
        return this;
    }

    public EnergyImportDTOBuilder WithL1MaxW(int value)
    {
        _l1MaxW = value;
        return this;
    }

    public EnergyImportDTOBuilder WithL2MaxW(int value)
    {
        _l2MaxW = value;
        return this;
    }

    public EnergyImportDTOBuilder WithL3MaxW(int value)
    {
        _l3MaxW = value;
        return this;
    }
    public EnergyImportDTO Build() => new EnergyImportDTO
    {
        Time = _time,
        ImportT1 = _importT1,
        ImportT2 = _importT2,
        ExportT1 = _exportT1,
        ExportT2 = _exportT2,
        L1MaxW = _l1MaxW,
        L2MaxW = _l2MaxW,
        L3MaxW = _l3MaxW
    };
}