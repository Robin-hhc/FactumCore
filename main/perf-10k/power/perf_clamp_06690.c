/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06690(unsigned int count)
{
    const unsigned int limit = 194u;
    return count > limit ? limit : count;
}
