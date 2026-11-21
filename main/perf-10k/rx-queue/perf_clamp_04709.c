/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04709(unsigned int count)
{
    const unsigned int limit = 132u;
    return count > limit ? limit : count;
}
