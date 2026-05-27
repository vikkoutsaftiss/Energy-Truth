using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services.Import;

public interface IImportService
{
    Task<List<EnergyImportDTO>> ProcessCsv(Stream fileStream, Dictionary<string, string> mapping, string providerName);

}
