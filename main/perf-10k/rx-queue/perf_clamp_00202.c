/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00202(unsigned int count)
{
    const unsigned int limit = 205u;
    return count > limit ? limit : count;
}
