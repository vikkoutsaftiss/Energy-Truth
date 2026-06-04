using Energy_Truth.Shared.EnergyLabel;
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Text;

namespace Energy_Truth.Shared.DTO_s
{
    public class CreateBuildingDTO
    {
        public int CustomerId { get; set; }
        [Required(ErrorMessage = "De postcode is verplicht.")]
        [MaxLength(6, ErrorMessage = "De postcode mag maximaal 6 tekens bevatten. De juiste opmaak is bijvoorbeeld 1234AB.")]
        public string PostalCode { get; set; } = "1234AB";
        [MaxLength(4, ErrorMessage = "Het bouwjaar mag maximaal 4 cijfers bevatten.")]
        public string? ConstructionYear { get; set; } = "2000";
        public ISTEnergyLabel ISTEnergyLabel { get; set; }
    }
}
