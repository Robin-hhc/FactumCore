/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01978(unsigned int count)
{
    const unsigned int limit = 19u;
    return count > limit ? limit : count;
}
