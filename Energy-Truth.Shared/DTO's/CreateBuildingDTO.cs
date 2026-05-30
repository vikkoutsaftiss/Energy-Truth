using Energy_Truth.Shared.EnergyLabel;
using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.DTO_s
{
    public class CreateBuildingDTO
    {
        public int CustomerId { get; set; }
        public string PostalCode { get; set; }
        public int? ConstructionYear { get; set; }
        public string? ISTEnergyLabel { get; set; }
    }
}
