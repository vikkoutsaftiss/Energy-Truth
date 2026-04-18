using Postgrest.Attributes;
using Postgrest.Models;
using System.Text.Json;// VOEG DEZE TOE

namespace Energy_Truth.Shared;

[Table("providers")]
public class ProviderDTO : BaseModel
{
    public Guid Id { get; set; }

    public string Code { get; set; }

    public string Name { get; set; }

    public DateTime CreatedAt { get; set; }
}
