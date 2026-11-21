/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07978(unsigned int count)
{
    const unsigned int limit = 178u;
    return count > limit ? limit : count;
}
