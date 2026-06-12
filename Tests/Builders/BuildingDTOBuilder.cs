using Energy_Truth.Shared.DTO_s;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.Builders
{
    public class BuildingDTOBuilder
    {
        private int _customerId = 1;
        private string _postalCode = "1234AB";
        private string _constructionYear = "2000";
        private string _istEnergyLabel = "A";

        public BuildingDTOBuilder WithCustomerId(int customerId)
        {
            _customerId = customerId;
            return this;
        }

        public BuildingDTOBuilder WithPostalCode(string postalCode)
        {
            _postalCode = postalCode;
            return this;
        }

        public BuildingDTOBuilder WithConstructionYear(string constructionYear)
        {
            _constructionYear = constructionYear;
            return this;
        }

        public BuildingDTOBuilder WithIstEnergyLabel(string istEnergyLabel)
        {
            _istEnergyLabel = istEnergyLabel;
            return this;
        }

        public BuildingDTO Build()
        {
            return new BuildingDTO
            {
                CustomerId = _customerId,
                PostalCode = _postalCode,
                ConstructionYear = _constructionYear,
                ISTEnergyLabel = _istEnergyLabel
            };
        }
    }
}
