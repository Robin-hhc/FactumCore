/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06651(unsigned int count)
{
    const unsigned int limit = 29u;
    return count > limit ? limit : count;
}
