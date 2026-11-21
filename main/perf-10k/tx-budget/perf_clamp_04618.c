/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04618(unsigned int count)
{
    const unsigned int limit = 79u;
    return count > limit ? limit : count;
}
