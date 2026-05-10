using Energy_Truth.Shared;
using Energy_Truth_WEB_API;

namespace Energy_Truth_WEB_API;

public interface IImportService
{
    Task<List<EnergyImportDTO>> ProcessCsv(Stream fileStream, Dictionary<string, string> mapping, string providerName);

}
