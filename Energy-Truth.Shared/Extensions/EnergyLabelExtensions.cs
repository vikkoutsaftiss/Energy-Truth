using Energy_Truth.Shared.EnergyLabel;
using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.Extensions
{
    public static class EnergyLabelExtensions
    {
        private static readonly Dictionary<ISTEnergyLabel, string> _labels = new()
    {
        { ISTEnergyLabel.APlusPlusPlusPlus, "A++++" },
        { ISTEnergyLabel.APlusPlusPlus, "A+++" },
        { ISTEnergyLabel.APlusPlus, "A++" },
        { ISTEnergyLabel.APlus, "A+" },
        { ISTEnergyLabel.A, "A" },
        { ISTEnergyLabel.B, "B" },
        { ISTEnergyLabel.C, "C" },
        { ISTEnergyLabel.D, "D" },
        { ISTEnergyLabel.E, "E" },
        { ISTEnergyLabel.F, "F" },
        { ISTEnergyLabel.G, "G" }
    };

        public static string ToDisplayString(this ISTEnergyLabel label)
        {
            return _labels[label];
        }

        public static ISTEnergyLabel FromDisplayString(this string label)
        {
            return _labels.FirstOrDefault(x => x.Value == label).Key;
        }
    }
}
