using Postgrest.Attributes;
using Postgrest.Models;
using Newtonsoft.Json; // VOEG DEZE TOE

namespace Energy_Truth.Shared;

[Table("providers")]
public class ProviderDTO : BaseModel
{
    public ProviderDTO() { } // Lege constructor

    [PrimaryKey("id", false)]
    [JsonProperty("id")] // Forceer Newtonsoft mapping
    public Guid Id { get; set; }

    [Column("code")]
    [JsonProperty("code")]
    public string Code { get; set; } = string.Empty;

    [Column("name")]
    [JsonProperty("name")]
    public string Name { get; set; } = string.Empty;

    [Column("created_at")]
    [JsonProperty("created_at")]
    public DateTime CreatedAt { get; set; }
}
